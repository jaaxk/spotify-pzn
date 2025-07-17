import torch
import torch.nn as nn
import torchaudio
from torch import Tensor
from pathlib import Path
from typing import List, Optional, Union, Dict, Any, Tuple
import logging
from transformers import AutoModel, Wav2Vec2FeatureExtractor

logger = logging.getLogger(__name__)

class MERTWrapper:
    """
    A wrapper for the MERT model that handles audio loading, preprocessing,
    and feature extraction.
    """
    _instance = None
    _model = None
    _processor = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MERTWrapper, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, model_name: str = "m-a-p/MERT-v1-330M", device: str = None):
        """
        Initialize the MERT wrapper.
        
        Args:
            model_name: Name of the MERT model to use
            device: Device to run the model on ('cuda' or 'cpu')
        """
        if not self._initialized:
            self.model_name = model_name
            self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
            self._load_model()
            self._initialized = True
        
    def _load_model(self):
        """Load the MERT model and processor."""
        if MERTWrapper._model is not None and MERTWrapper._processor is not None:
            self.model = MERTWrapper._model
            self.processor = MERTWrapper._processor
            return
            
        try:
            logger.info(f"Loading MERT model {self.model_name}...")
            # Load model with trust_remote_code=True as in test.py
            MERTWrapper._model = AutoModel.from_pretrained(
                self.model_name, 
                trust_remote_code=True
            ).to(self.device)
            MERTWrapper._model.eval()
            
            # Load processor with trust_remote_code=True as in test.py
            MERTWrapper._processor = Wav2Vec2FeatureExtractor.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            self.model = MERTWrapper._model
            self.processor = MERTWrapper._processor
            
            logger.info(f"MERT model loaded on {self.device}")
        except Exception as e:
            logger.error(f"Error loading MERT model: {e}")
            raise
    
    def _load_audio(self, audio_path: Union[str, Path], target_sr: int = 24000) -> Tensor:
        """Load and preprocess an audio file."""
        waveform, sample_rate = torchaudio.load(audio_path)
        
        # Convert to mono if needed
        if waveform.dim() > 1 and waveform.shape[0] > 1:
            print('CONVERTING TO MONO')
            waveform = torch.mean(waveform, dim=0, keepdim=True)
            
        # Resample if needed
        if sample_rate != target_sr:
            print('RESAMPLING')
            if self.resampler is None or self.resampler.orig_freq != sample_rate:
                self.resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate,
                    new_freq=target_sr
                )
            waveform = self.resampler(waveform)
            
        return waveform.squeeze()  # [num_samples]
    
    def get_embeddings(
        self, 
        audio_path: Union[str, Path],
        layer: int = -1,  # -1 for last layer
        reduce: str = 'mean'  # 'mean', 'max', or 'none'
    ) -> Dict[str, Any]:
        """
        Extract embeddings from an audio file.
        
        Args:
            audio_path: Path to the audio file
            layer: Which layer's hidden states to return (-1 for last layer)
            reduce: How to reduce the time dimension ('mean', 'max', or 'none')
            
        Returns:
            Dictionary containing:
            - 'embeddings': The extracted embeddings
            - 'hidden_states': All hidden states if return_hidden_states=True
            - 'attention': Attention weights if available
        """
        if self.model is None or self.processor is None:
            self.load()
            
        # Load and preprocess audio
        waveform = self._load_audio(audio_path)
        
        # Process through feature extractor
        inputs = self.processor(
            waveform.numpy(),
            sampling_rate=self.processor.sampling_rate,
            return_tensors="pt",
            padding=True,
            return_attention_mask=True
        ).to(self.device)
        
        # Get model outputs
        with torch.no_grad():
            outputs = self.model(
                **inputs,
                output_hidden_states=True,
                output_attentions=True
            )
        
        # Process hidden states
        hidden_states = torch.stack(outputs.hidden_states)  # [num_layers, batch, seq_len, hidden_size]
        
        # Get embeddings from the specified layer
        embeddings = hidden_states[layer].squeeze(0)  # [seq_len, hidden_size]
        
        # Reduce time dimension if needed
        if reduce == 'mean':
            embeddings = embeddings.mean(dim=0)  # [hidden_size]
        elif reduce == 'max':
            embeddings = torch.max(embeddings, dim=0)[0]  # [hidden_size]
        
        # Prepare output
        result = {
            'embeddings': embeddings.cpu().numpy(),
            'hidden_states': hidden_states.cpu().numpy() if outputs.hidden_states else None,
            'attention': outputs.attentions[-1].cpu().numpy() if outputs.attentions else None,
            'audio_path': str(audio_path)
        }
        
        return result
    
    def process_directory(
        self, 
        input_dir: Union[str, Path],
        output_file: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Process all audio files in a directory.
        
        Args:
            input_dir: Directory containing audio files
            output_file: Optional path to save results as a .pt file
            **kwargs: Additional arguments to pass to get_embeddings
            
        Returns:
            List of results from get_embeddings for each file
        """
        print('PROCESSING DIRECTORY')
        input_dir = Path(input_dir)
        if not input_dir.exists() or not input_dir.is_dir():
            raise NotADirectoryError(f"Input directory not found: {input_dir}")
            
        # Supported audio formats
        audio_extensions = {'.wav', '.mp3', '.flac', '.ogg'}
        audio_files = [f for f in input_dir.glob('*') if f.suffix.lower() in audio_extensions]
        
        if not audio_files:
            logger.warning(f"No audio files found in {input_dir}")
            return []
            
        results = []
        for audio_file in audio_files:
            print(f'Processing file')
            try:
                logger.info(f"Processing {audio_file.name}...")
                result = self.get_embeddings(audio_file, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {audio_file}: {e}")
                continue
                
        print('RETURNING RESULTS')
        # Save results if output file is specified
        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            torch.save(results, output_file)
            logger.info(f"Saved results to {output_file}")
            
        return results
