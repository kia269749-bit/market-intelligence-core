from mi_core.microstructure import cross_exchange_confirmation

def test_low_quality_exchange_does_not_confirm():
    result = cross_exchange_confirmation(
        [{"score":0.8,"quality":0.95},{"score":0.7,"quality":0.90},{"score":0.6,"quality":0.20}]
    )
    assert result["qualified_exchanges"] == 2
    assert result["confirmed"] is True

def test_two_good_exchanges_confirm():
    result = cross_exchange_confirmation(
        [{"score":0.8,"quality":0.90},{"score":0.7,"quality":0.85}]
    )
    assert result["confirmed"] is True
    assert result["qualified_exchanges"] == 2
