# Verification evidence

Proof artifacts from running `.cursor/skills/verify-chinagovernance` live here, one subdirectory per `VERIFY_RUN_ID`.

Cleanup deletes the isolated uvicorn process and `/tmp/verify-chinagovernance-*` scratch (including the fixture SQLite). **It must not delete this directory.**

Do not copy production `documents.db` into this tree.
