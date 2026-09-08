"""Public research-workbench CLI; preserves the existing deployment identity.

The compatibility implementation keeps its original Compose project, database
credential derivation and data volumes. This entry never creates a model run.
"""
from scripts.deployment.dell_report_workbench import main


if __name__ == "__main__":
    main()
