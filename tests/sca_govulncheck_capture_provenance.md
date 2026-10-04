# Provenance of sca_govulncheck_capture.txt

govulncheck version: v1.8.0
go version: go1.27.1
command: go run golang.org/x/vuln/cmd/govulncheck@v1.8.0 -json ./...
capture date: 2026-10-04 (JST)
go.mod:

```
module example.com/vulnprobe

go 1.20

require golang.org/x/text v0.3.6
```

- The command ran in the root of a scratch module outside this repository; the scratch module is not committed.
- The module's main package imports `golang.org/x/text/language` and calls `language.ParseAcceptLanguage`.
- `sca_govulncheck_capture.txt` is the command's stdout, unmodified. The output held no machine-local absolute path, so no placeholder token was applied.
