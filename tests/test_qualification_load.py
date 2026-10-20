from scripts.engineering.qualification_load import distribution, measure


def test_nearest_rank_percentiles_keep_tail_and_empty_samples():
    assert distribution([]) == {'n': 0}
    result = distribution(list(range(1, 101)))
    assert (result['p50_ms'], result['p95_ms'], result['p99_ms'], result['max_ms']) == (50, 95, 99, 100)


def test_closed_loop_counts_each_request_and_retains_wrong_results_and_failures():
    def operation(index, worker):
        if index == 3:
            raise TimeoutError('secret response text must not escape into metrics')
        return {'ok': index != 5, 'status': 200, 'identity': f'user-{worker}'}
    result = measure(operation, concurrency=4, requests=17)
    assert result['completed'] == 17 and result['correct'] == 15 and result['failed'] == 2
    assert result['not_started'] == 0
    assert result['all_terminal_latency']['n'] == 17 and result['correct_latency']['n'] == 15
    assert [r['index'] for r in result['samples']] == list(range(17))
    assert len({r['worker'] for r in result['samples']}) == 4
    assert result['samples'][3]['result'] == {'ok': False, 'error_type': 'TimeoutError'}
    assert result['success_rate'] == 15/17


def test_resource_stop_withholds_new_requests_without_claiming_success():
    calls = []
    result = measure(lambda i, w: (calls.append(i) or {'ok': True}),
        concurrency=1, requests=10, should_continue=lambda: len(calls) < 3)
    assert result['completed'] == 3 and result['not_started'] == 7
