"""Serial resource limits are opt-in and cannot replace the production BFF."""
from tests.integration.source_intake_runtime import CompleteSourceStack, OrganizationGraphStack, SERIAL_ENV


def test_serial_limits_are_local_to_the_opted_in_stack(tmp_path, monkeypatch):
    def initialize(self):
        self.output = tmp_path
        self.env = {'existing': 'retained'}
    monkeypatch.setattr(OrganizationGraphStack, '__init__', initialize)
    monkeypatch.setenv('FIN_COMPLETE_SOURCE_SERIAL_PROFILE', '1')
    serial = CompleteSourceStack()
    assert serial.env['existing'] == 'retained'
    assert all(serial.env[k] == value for k, value in SERIAL_ENV.items())
    assert serial.compose_files[-1].name == 'source_intake_serial.compose.yaml'
    assert serial.bff_arguments == ('--workers', '1', '--limit-concurrency', '8', '--backlog', '16')
    monkeypatch.delenv('FIN_COMPLETE_SOURCE_SERIAL_PROFILE')
    original = CompleteSourceStack()
    assert original.env == {'existing': 'retained'}
    assert original.bff_arguments == ()
    assert all(path.name != 'source_intake_serial.compose.yaml' for path in original.compose_files)


def test_bff_launcher_keeps_same_app_and_passes_only_instance_arguments(tmp_path, monkeypatch):
    from tests.integration import test_java_intake_native as module
    stack = object.__new__(CompleteSourceStack)
    stack.java, stack.jar, stack.bff_port = 'unused', 'unused', 19001
    stack.output, stack.logs, stack.processes = tmp_path, [], []
    stack.env = {'LANGSMITH_API_KEY': 'test-only', 'other': 'retained'}
    stack.bff_arguments = ('--workers', '1', '--limit-concurrency', '8')
    seen = []
    monkeypatch.setattr(module.subprocess, 'Popen', lambda args, **kw: seen.append((args, kw)) or object())
    monkeypatch.setattr(module, 'ready', lambda *args: None)
    stack.boot('bff')
    args, options = seen[0]
    assert 'tests.integration.fixtures.intake_native_web:app' in args
    assert args[-4:] == ['--workers', '1', '--limit-concurrency', '8']
    assert 'LANGSMITH_API_KEY' not in options['env']
    for log in stack.logs: log.close()


def test_optional_dependencies_do_not_modify_shared_interpreter_or_parent_environment(tmp_path, monkeypatch):
    def initialize(self):
        self.output = tmp_path
        self.env = {'PYTHONPATH':'repository-source'}
    monkeypatch.setattr(OrganizationGraphStack, '__init__', initialize)
    monkeypatch.setenv('PYTHONPATH','parent-source')
    monkeypatch.setenv('FIN_QUALIFICATION_DEPENDENCY_ROOT', str(tmp_path))
    stack = CompleteSourceStack()
    import os
    assert stack.env['PYTHONPATH'] == os.pathsep.join(['repository-source',str(tmp_path.resolve())])
    assert os.environ['PYTHONPATH'] == 'parent-source'
