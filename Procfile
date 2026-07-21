# Single worker: in-memory sync-job state must live in one process.
# Threads handle concurrent requests; sync itself runs in its own thread.
release: flask --app api migrate-parrygg
web: gunicorn run:app --workers 1 --threads 8 --timeout 120
