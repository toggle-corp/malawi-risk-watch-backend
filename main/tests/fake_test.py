from django.test import TestCase


class FakeTest(TestCase):
    """Test for running migrations only.

    docker-compose run --rm web ./manage.py test  --pattern="main/tests/test_fake.py"
    """

    def test_fake(self):
        pass
