You are evaluating how well you can understand this workspace by reading its CURRENT source code. This is a read-only comprehension task: do not propose or make edits, and do not start servers or run commands.

Answer each question from the code itself. For every claim, give evidence as a repo-relative file path plus line numbers (or a function name) from the source file that implements it. Citing documentation is allowed but does not replace a code citation. If you cannot verify something in code, say so in "uncertainties" instead of guessing.

Questions (browser page and HTTP server):

Q1. When the browser requests `/app.js` and `/styles.css`, which files on disk are actually served, with which Content-Type values, and where is that mapping defined? What caching header do responses carry?
Q2. What is the largest POST body the server accepts? What status code and error code does a larger body get, and where is that enforced? What happens to a request that uses a Transfer-Encoding body?
Q3. What does the server return for `GET /api/runs`, including any header that tells the client which method is allowed?
Q4. How long does the page wait for an API response before giving up, how is that enforced in the browser code, and why was that value chosen?
Q5. Describe exactly what the page does after a POST (new run or recovery) fails at the transport level or returns an uncertain/error result. Does it ever retry the POST? Which state does it re-read?
Q6. How does the page display evidence values that the server reports as null?
Q7. Which element ids / test hooks identify the two action buttons?
Q8. What prevents one idle browser connection from blocking the server, and what prevents a second server process from silently sharing the same port?

Return the structured output required by the provided JSON schema, with one entry per question id (Q1..Q8).
