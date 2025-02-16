try:
	git add .
	pre-commit try-repo .
mimic-try:
	git add .
	npm install --include=dev --include=prod --ignore-prepublish --no-progress --no-save .
	npm pack
	npm install -g pyright-pretty-1.0.0.tgz
	which pyright-pretty
	pyright-pretty --help
