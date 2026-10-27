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

COMPACT_ENV = {
    'JAVA_TOOL_OPTIONS': '-Xms16m -Xmx128m -XX:+UseSerialGC -XX:ActiveProcessorCount=2 '
                         '-XX:ReservedCodeCacheSize=32m -XX:MaxMetaspaceSize=128m '
                         '-XX:MaxDirectMemorySize=16m -Xss512k',
    'SERVER_TOMCAT_THREADS_MAX': '4',
    'SERVER_TOMCAT_MAX_CONNECTIONS': '12',
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
        self.compact_profile = os.getenv('FIN_COMPLETE_SOURCE_COMPACT_PROFILE') == '1'
        if self.compact_profile and not self.serial_profile:
            raise ValueError('compact_source_intake_requires_serial_profile')
        if self.serial_profile:
            self.compose_files = (*self.compose_files, ROOT/'deploy/qualification/source_intake_serial.compose.yaml')
            self.env.update(SERIAL_ENV)
            self.bff_arguments = ('--workers', '1', '--limit-concurrency', '8', '--backlog', '16')
        if self.compact_profile:
            self.compose_files = (*self.compose_files, ROOT/'deploy/qualification/source_intake_compact.compose.yaml')
            self.env.update(COMPACT_ENV)
            self.bff_arguments = ('--workers', '1', '--limit-concurrency', '8', '--backlog', '8')
        self.save('source-intake-runtime', {'serial_profile': self.serial_profile,
                  'compact_profile': self.compact_profile,
                  'optional_dependency_root': str(dependency_root) if dependency_root else None,
                  'limits': {**SERIAL_ENV, **(COMPACT_ENV if self.compact_profile else {})} if self.serial_profile else {},
                  'bff_app': 'tests.integration.fixtures.intake_native_web:app',
                  'production_routes_unchanged': True, 'capacity_evaluation': False})
        if os.getenv('FIN_COMPLETE_SOURCE_HTTP_QUALITY') == '1':
            if not self.compact_profile:
                raise ValueError('http_quality_requires_frozen_compact_profile')
            self.env.update(FINSIGHT_ORGANIZATION_NAVIGATION_ENABLED='1',
                FINSIGHT_ORGANIZATION_CANDIDATE_POLICY='needs_window.v4',
                FINSIGHT_ORGANIZATION_TABLE_COMPLETION='bounded.v1',
                FINSIGHT_ORGANIZATION_QUERY_EMBEDDING='qwen',
                FINSIGHT_ORGANIZATION_RERANK='qwen',
                FINSIGHT_ORGANIZATION_RERANK_MODEL='qwen3.7-text-rerank')

    def boot(self, which):
        # Only the explicitly budgeted BFF receives a provider key. Neither
        # PostgreSQL nor the Java process or an Agent container needs it.
        if which == 'bff' and os.getenv('FIN_COMPLETE_SOURCE_HTTP_QUALITY') == '1':
            self.env['QWEN_API_KEY'] = os.environ['QWEN_API_KEY']
            try:
                process = super().boot(which)
            finally:
                self.env.pop('QWEN_API_KEY', None)
        else:
            process = super().boot(which)
        if os.getenv('FIN_COMPLETE_SOURCE_HTTP_QUALITY') == '1':
            import psutil
            owned = psutil.Process(process.pid)
            cpus = psutil.Process().cpu_affinity()[:2]
            owned.cpu_affinity(cpus)
            self.save(which+'-fixed-process-resources', {'pid': process.pid, 'logical_cpu_affinity': owned.cpu_affinity(),
                'java_heap_mib': 128 if which == 'java' else None,
                'python_worker_count': 1 if which == 'bff' else None,
                'python_memory_hard_cap': False, 'shared_host': True})
        return process

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
