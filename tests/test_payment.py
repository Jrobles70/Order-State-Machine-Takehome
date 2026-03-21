def test_authorize_success_default_card():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    result = provider.authorize("4242424242424242", 100.00)
    assert result.success is True
    assert result.authorization_id is not None
    assert result.error == ""


def test_authorize_decline():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    result = provider.authorize("4000000000000002", 100.00)
    assert result.success is False
    assert result.authorization_id is None
    assert result.error != ""


def test_capture_success_default_card():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    auth = provider.authorize("4242424242424242", 100.00)
    result = provider.capture(auth.authorization_id)
    assert result.success is True


def test_capture_fails_for_capture_fail_card():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    auth = provider.authorize("4000000000000341", 100.00)
    result = provider.capture(auth.authorization_id)
    assert result.success is False
    assert result.error != ""


def test_void_succeeds_for_capture_fail_card():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    auth = provider.authorize("4000000000000341", 100.00)
    result = provider.void(auth.authorization_id)
    assert result.success is True


def test_capture_fails_and_void_fails():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    auth = provider.authorize("4000000000009995", 100.00)
    capture_result = provider.capture(auth.authorization_id)
    assert capture_result.success is False
    void_result = provider.void(auth.authorization_id)
    assert void_result.success is False


def test_fulfillment_fail_card_capture_succeeds():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    auth = provider.authorize("4000000000000259", 100.00)
    result = provider.capture(auth.authorization_id)
    assert result.success is True


def test_should_fail_fulfillment():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    auth = provider.authorize("4000000000000259", 100.00)
    assert provider.should_fail_fulfillment(auth.authorization_id) is True


def test_should_not_fail_fulfillment_default():
    from app.payment import StubPaymentProvider

    provider = StubPaymentProvider()
    auth = provider.authorize("4242424242424242", 100.00)
    assert provider.should_fail_fulfillment(auth.authorization_id) is False
