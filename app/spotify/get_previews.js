require('dotenv').config();
const fs = require('fs');
const finder = require('spotify-preview-finder');

async function enhancedSearch() {
  const tracks = JSON.parse(fs.readFileSync('tracks.json', 'utf8'));
  const results = {};
  let foundCount = 0;

  for (const track of tracks) {
    const { name, artist } = track;
    const key = `${name} - ${artist}`;
    try {
      const result = await finder(name, artist, 2);

      if (result.success && result.results.length > 0) {
        const song = result.results[0];
        const previewUrls = song.previewUrls || [];

        results[key] = previewUrls.length > 0 ? previewUrls[0] : null;

        console.log(`✅ Found preview for: ${song.name} by ${artist}`);
        console.log(`   Album: ${song.albumName}`);
        console.log(`   Track ID: ${song.trackId}`);
        console.log(`   Preview URLs (${previewUrls.length}):`);
        previewUrls.forEach(url => console.log(`     - ${url}`));

        if (previewUrls.length > 0) {
          foundCount++;
        } else {
          console.log("   ⚠️  No preview URLs returned.");
        }

      } else {
        results[key] = null;
        console.log(`❌ No match or preview found for: ${key}`);
        if (result.error) console.log(`   Error: ${result.error}`);
      }

    } catch (error) {
      console.error(`🔥 Error during search for ${key}: ${error.message}`);
      results[key] = null;
    }

    console.log('--------------------------------------------------');
  }

  fs.writeFileSync('preview_urls.json', JSON.stringify(results, null, 2));
  console.log(`\n🎧 Found previews for ${foundCount} out of ${tracks.length} tracks.`);
}

enhancedSearch();
