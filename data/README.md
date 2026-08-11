# Local data boundary

This directory is the default local `FINSIGHT_DATA_ROOT`. Private source files,
indexes, databases, model captures and Workbench state are Git-ignored and may
instead be mounted from another location.

Only this README belongs to the repository. A clean checkout must pass the
public baseline tests without copying workstation data into Git. Tests or runs
that require private assets must declare that dependency and use an explicit
data root.
