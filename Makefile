# Testen als Teil des Entwicklungsprozesses

# Definiere Befehle für verschiedene Testphasen
.PHONY: precommit postdeploy test


# precommit Tests: also solche die im Code explizit mit @pytest.mark.precommit markiert sind
precommit:
	pytest -m precommit


# nur postdeploy Tests: also solche die im Code explizit mit @pytest.mark.postdeploy markiert sind
postdeploy:
	pytest -m postdeploy

# alle Tests
test:
	pytest
