# Für die Erstellung des Claude Ansatzes

- Nur im Verzeichnis .claude schreibende Zugriffe ausführen.
- Auf alle anderen Verzeichnisse und Dateien parallel zu .claude nur lesend zugreifen
- Sicherstellen dass keine Secrets in GitHub eingecheckt werden, insbesondere auch die Datei settings.local.json nicht
- Es soll kein git commit automatisch ausgeführt werden
- Auf den Raspberry soll nicht direkt zugegriffen werden - weder schreibend noch mit Aufrufen wie zum Beispiel um auf dem Raspberry git pull oder ein deployment auszuführen
- Erhalte den versions- und idempotenz-getriebenen Ansatz
- Transformiere den implementierten Ansatz im Repository sowie insbesonder auch in der Root-Datei ChatGPTHint.txt in entsprechende Claude Artefakte
- Erweitere auch diese Datei entsprechend durch Anfügen von Informationen
