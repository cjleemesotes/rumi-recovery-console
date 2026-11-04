# Frontend: Rumi recovery console page

Plain HTML/CSS/JS, no build step. The Python backend serves it (see `backend/`).

| File | Role |
|---|---|
| `index.html` | Page structure, DOM ids and `data-testid` hooks. Keeps the public asset URLs `styles.css` and `app.js`. |
| `assets/js/console.js` | One cohesive script: request/response handling, state, rendering. Served at the public URL `/app.js`. |
| `assets/css/console.css` | All styling (light/dark tokens, layout). Served at the public URL `/styles.css`. |

The backend maps `/app.js` to `assets/js/console.js` and `/styles.css` to `assets/css/console.css`; the HTML does not reference the `assets/` paths.

API used (relative URLs): `GET api/state`, `POST api/runs`, `POST api/runs/{run_id}/recover`.
