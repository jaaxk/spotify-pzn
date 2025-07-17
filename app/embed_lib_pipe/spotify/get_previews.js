require('dotenv').config();
const fs = require('fs');
const spotifyPreviewFinder = require('spotify-preview-finder');

// Verify required environment variables
const requiredVars = ['SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET'];
const missingVars = requiredVars.filter(varName => !process.env[varName]);

if (missingVars.length > 0) {
    console.error('❌ Error: Missing required environment variables:', missingVars.join(', '));
    process.exit(1);
}

// Log that we have the required credentials
console.log('✅ Found required Spotify credentials');

async function processTracks() {
  try {
    console.log("Starting preview finder script...");
    
    // Read and parse tracks file
    const tracksFile = 'data/tracks.json';
    console.log(`Reading tracks from ${tracksFile}...`);
    
    if (!fs.existsSync(tracksFile)) {
      throw new Error(`${tracksFile} not found`);
    }
    
    const tracksData = fs.readFileSync(tracksFile, 'utf8');
    if (!tracksData.trim()) {
      throw new Error(`${tracksFile} is empty`);
    }
    
    const tracks = JSON.parse(tracksData);
    console.log(`Found ${tracks.length} tracks to process`);
    
    if (!Array.isArray(tracks)) {
      throw new Error('Expected tracks to be an array');
    }
    
    const results = {};
    let foundCount = 0;
    let processedCount = 0;

    for (const track of tracks) {
      processedCount++;
      const name = track?.name || '';
      const artist = track?.artist || '';
      const key = `${name} - ${artist}`.trim();
      
      if (!name || !artist) {
        console.log(`⚠️  Skipping track ${processedCount}/${tracks.length}: Missing name or artist`);
        results[key] = null;
        continue;
      }
      
      console.log(`\n🔍 Processing track ${processedCount}/${tracks.length}: ${key}`);
      
      try {
        console.log(`🔍 Searching for: ${name} by ${artist}`);
        // Pass credentials directly in the search call
        const result = await spotifyPreviewFinder(
            name,
            artist,
            2, // limit
            {
                clientId: process.env.SPOTIFY_CLIENT_ID,
                clientSecret: process.env.SPOTIFY_CLIENT_SECRET
            }
        );
        
        if (result?.success && result.results?.length > 0) {
          console.log(`✅ Found ${result.results.length} results for: ${key}`);
          console.log(`Search Query Used: ${result.searchQuery}`);
          
          // Take the first result
          const song = result.results[0];
          const previewUrls = song.previewUrls || [];
          const previewUrl = previewUrls.length > 0 ? previewUrls[0] : null;
          
          results[key] = previewUrl;
          
          if (previewUrl) {
            foundCount++;
            console.log(`🎵 Track: ${song.name}`);
            console.log(`   Artist: ${song.artists?.[0]?.name || artist}`);
            console.log(`   Album: ${song.albumName || 'N/A'}`);
            console.log(`   Track ID: ${song.trackId || 'N/A'}`);
            console.log(`   Preview URL: ${previewUrl}`);
          } else {
            console.log(`⚠️  No preview URL available for: ${key}`);
          }
        } else {
          results[key] = null;
          console.log(`❌ No matches found for: ${key}`);
          if (result?.error) {
            console.log(`   Error: ${result.error}`);
          }
        }
      } catch (error) {
        console.error(`🔥 Error during search for ${key}:`, error.message);
        console.error(error.stack);
        results[key] = null;
      }
      
      // Add a small delay between requests to avoid rate limiting
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    // Save results
    const outputFile = 'data/preview_urls.json';
    fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
    console.log(`\n🎧 Found previews for ${foundCount} out of ${tracks.length} tracks.`);
    console.log(`Results saved to ${outputFile}`);
    
    return results;
    
  } catch (error) {
    console.error('🔥 Fatal error in processTracks:', error);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run the main function
processTracks().catch(error => {
  console.error('🔥 Unhandled error in processTracks:', error);
  console.error(error.stack);
  process.exit(1);
});
