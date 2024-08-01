# Magql Example - Upload

This example shows how to upload, store, and download files using Magql,
Magql-SQLAlchemy, and Flask-Magql.

```text
$ python -m venv .venv
$ . .venv/bin/activate
$ pip install -e .
$ flask run
```

You can use curl to upload a file, since graphiql and conveyor-admin don't
currently support file uploads.

```text
$ echo "Hello, World!" > hello.txt
$ curl http://127.0.0.1:5000/graphql \
  -F operations='{"query": "query($title: String!, $file: Upload!) {
    document_create(title: $title, file: $file) {
      id title filename file_url
    }
  }", "variables": {"title": "Hello", "file": null}}' \
  -F map='{"0": ["variables.file"]}' \
  -F 0=hello.txt
{
  "id": 1,
  "title": "Hello",
  "filename": "hello.txt",
  "file_url": "http://127.0.0.1:5000/document/download/1"
}
```

You'll see a file at `instance/document/1_file`, and can download it with curl:

```text
$ curl http://127.0.0.1:5000/document/download/1
Hello, World!
```
