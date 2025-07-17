print('running')
# from transformers import Wav2Vec2Processor
from transformers import Wav2Vec2FeatureExtractor
from transformers import AutoModel
import torch
from torch import nn
import torchaudio.transforms as T
from datasets import load_dataset

# loading our model weights
model = AutoModel.from_pretrained("m-a-p/MERT-v1-330M", trust_remote_code=True)
# loading the corresponding preprocessor config
processor = Wav2Vec2FeatureExtractor.from_pretrained("m-a-p/MERT-v1-330M",trust_remote_code=True)

import torch
from torch import nn
import torchaudio
import torchaudio.transforms as T
from transformers import AutoModel, Wav2Vec2FeatureExtractor

# Load MERT model and processor
model = AutoModel.from_pretrained("m-a-p/MERT-v1-330M", trust_remote_code=True)
processor = Wav2Vec2FeatureExtractor.from_pretrained("m-a-p/MERT-v1-330M", trust_remote_code=True)

# Load audio file
waveform, sampling_rate = torchaudio.load("space_song_10s.wav")  # shape: [1, num_samples]
waveform = waveform.squeeze()  # shape: [num_samples]

# Resample if needed
resample_rate = processor.sampling_rate
if sampling_rate != resample_rate:
    print(f"Resampling from {sampling_rate} to {resample_rate}")
    resampler = T.Resample(orig_freq=sampling_rate, new_freq=resample_rate)
    waveform = resampler(waveform)

# Run through processor
inputs = processor(waveform.numpy(), sampling_rate=resample_rate, return_tensors="pt")

# Extract hidden states from all layers
with torch.no_grad():
    outputs = model(**inputs, output_hidden_states=True)

all_layer_hidden_states = torch.stack(outputs.hidden_states).squeeze()
print("All hidden states shape:", all_layer_hidden_states.shape)  # [25, T, 1024]

# Mean across time dimension to get one vector per layer
time_reduced_hidden_states = all_layer_hidden_states.mean(dim=1)
print("Time-reduced shape:", time_reduced_hidden_states.shape)  # [25, 1024]

# Optional: Learnable weighted average over the 25 layers
aggregator = nn.Conv1d(in_channels=25, out_channels=1, kernel_size=1)
weighted_avg_hidden_states = aggregator(time_reduced_hidden_states.unsqueeze(0)).squeeze()
print("Final embedding shape:", weighted_avg_hidden_states.shape)  # [1024]
