from cryptoadvance.specterext.spectrum.controller_helpers import evaluate_current_status

def test_evaluate_current_status():
    node_is_running_before_request, success, host_before_request, host_after_request = False, True, False, True
    changed_host, check_port_and_ssl = evaluate_current_status(node_is_running_before_request, success, host_before_request, host_after_request)
    assert changed_host == True
    assert check_port_and_ssl == False