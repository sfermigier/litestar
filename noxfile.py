import nox

nox.options.sessions = ["lint", "test"]
nox.options.reuse_existing_virtualenvs = True

PYTHON_VERSIONS = ["3.10", "3.11", "3.12"]


@nox.session(python=PYTHON_VERSIONS[0])
def lint(session: nox.Session) -> None:
    session.install(".")
    session.install("abilian-devtools")
    session.run("black", "--check", "litestar", "tests")
    session.run("ruff", "litestar", "tests")
    # session.run("adt", "check", "litestar", "tests")


@nox.session(python=PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    session.install("poetry")
    session.run("poetry", "install", "--all-extras")
    session.run("pip", "check")
    session.run("pytest")
