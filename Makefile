.PHONY: test diagnose serve

test:
	python3 -m unittest discover -s tests

diagnose:
	python3 -m k8s_assistant.cli diagnose --namespace default

serve:
	python3 -m k8s_assistant.cli serve --host 127.0.0.1 --port 8080
