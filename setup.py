# stratlab/setup.py
from setuptools import setup, find_packages

setup(
    name="stratlab",
    version="0.1",
    packages=find_packages(),  # finds app, backend, tests
    CELERY_TASK_ALWAYS_EAGER = True,
    CELERY_TASK_EAGER_PROPAGATES = True
)
