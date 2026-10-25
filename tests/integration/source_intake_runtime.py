"""Resource configuration for serial intake; all production handlers stay installed."""
import json
import os
import subprocess
from pathlib import Path

from tests.integration.test_organization_graph_native import OrganizationGraphStack
from tests.integration.test_java_intake_native import ROOT

SERIAL_ENV = {
    'JAVA_TOOL_OPTIONS': '-Xms32m -Xmx256m -XX:+UseSerialGC -XX:ActiveProcessorCount=2 '
                         '-XX:ReservedCodeCacheSize=48m -XX:MaxMetaspaceSize=160m '
                         '-XX:MaxDirectMemorySize=32m -Xss512k',
    'SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE': '2',
    'SPRING_DATASOURCE_HIKARI_MINIMUM_IDLE': '1',
    'SERVER_TOMCAT_THREADS_MAX': '8',
    'SERVER_TOMCAT_THREADS_MIN_SPARE': '1',
    'SERVER_TOMCAT_MAX_CONNECTIONS': '16',
    'SERVER_TOMCAT_ACCEPT_COUNT': '8',
    'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
    'NUMEXPR_MAX_THREADS': '1',
}


class CompleteSourceStack(OrganizationGraphStack):
    def __init__(self):
        super().__init__()
        dependency_root = os.getenv('FIN_QUALIFICATION_DEPENDENCY_ROOT')
        if dependency_root:
            dependency_root = Path(dependency_root).resolve(strict=True)
            if not dependency_root.is_dir():
                raise ValueError('qualification_dependency_root_must_be_directory')
            self.env['PYTHONPATH'] = os.pathsep.join(filter(None, [self.env.get('PYTHONPATH'), str(dependency_root)]))
        self.serial_profile = os.getenv('FIN_COMPLETE_SOURCE_SERIAL_PROFILE') == '1'
        if self.serial_profile:
            self.compose_files = (*self.compose_files, ROOT/'deploy/qualification/source_intake_serial.compose.yaml')
            self.env.update(SERIAL_ENV)
            self.bff_arguments = ('--workers', '1', '--limit-concurrency', '8', '--backlog', '16')
        self.save('source-intake-runtime', {'serial_profile': self.serial_profile,
                  'optional_dependency_root': str(dependency_root) if dependency_root else None,
                  'limits': SERIAL_ENV if self.serial_profile else {},
                  'bff_app': 'tests.integration.fixtures.intake_native_web:app',
                  'production_routes_unchanged': True, 'capacity_evaluation': False})

    def postgres_memory_evidence(self):
        """Read only this attempt's cgroup peak, before its container is stopped."""
        ids = subprocess.check_output([self.docker, 'ps', '-q', '--filter',
             'label=com.docker.compose.project='+self.project, '--filter',
             'label=com.docker.compose.service=postgres'], text=True, timeout=10).split()
        if len(ids) != 1:
            self.save('postgres-memory', {'status': 'unavailable', 'reason': 'own_postgres_not_running'})
            return
        result = subprocess.run([self.docker, 'exec', ids[0], 'cat', '/sys/fs/cgroup/memory.peak'],
                                capture_output=True, text=True, timeout=10)
        state = json.loads(subprocess.check_output([self.docker, 'inspect', '--format',
                              '{{json .State}}', ids[0]], text=True, timeout=10))
        self.save('postgres-memory', {'status': 'observed' if result.returncode == 0 else 'unavailable',
            'peak_cgroup_bytes': int(result.stdout.strip()) if result.returncode == 0 else None,
            'oom_killed': state.get('OOMKilled'), 'container_id': ids[0],
            'scope': 'own PostgreSQL cgroup including its cache; not all WSL'})
