# Contributing

Use Python3.12 x64 and a virtual environment. Keep geometry/physics values in SI and preserve existing project-schema compatibility. Avoid overwriting user cases or machine profiles. Keep Chinese/English labels synchronized.

Run `python -m compileall -q off installer app.py` and `python tests/public_smoke.py`. GitHub CI covers syntax and model/topology contracts only. CFD/UI/WSL acceptance needs a local Windows machine and real Foundation14 environment; record cells, MPI ranks, model, exact times, solver errors and actual export checks. Do not describe smoke tests as physical convergence.

Submit a focused PR describing observable behavior and validation. Do not include credentials, private keys, user queue databases or simulation datasets. Report issues using the templates.
