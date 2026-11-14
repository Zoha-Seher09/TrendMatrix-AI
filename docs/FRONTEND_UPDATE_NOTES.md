TrendMatrix AI — Interactive Earth Observatory frontend
========================================================

Included replacement files:
- templates/dashboard.html
- static/css/style.css
- static/js/dashboard.js

Install
-------
1. Extract this ZIP into the Trend_Matrix_AI project root and allow overwrite.
2. The backend is unchanged. Existing Flask routes are used:
   - GET /api/geocode?q=...
   - POST /api/analyze
3. Start Flask as usual and open http://127.0.0.1:5000.

Important
---------
- The 3D globe uses Globe.gl and its Earth texture from public CDNs, so an
  internet connection is required for the globe and texture to load.
- If the globe CDN is unavailable, the rest of the dashboard and existing
  NASA analysis API remain separate; refresh after restoring internet access.
- Globe clicks select coordinates. Search results select named places.
- The globe is a geographic selector, not a NASA raster/data-layer map.
  NASA POWER observations remain point-based for the selected coordinates.
- The selector exposes only the five NASA POWER variables currently
  supported by the live analysis pipeline.
- No Python/backend source files are included or changed.
