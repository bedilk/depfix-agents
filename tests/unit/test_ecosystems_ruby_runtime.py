"""Unit tests for Ruby install/test/smoke plumbing
(``ecosystems/ruby_runtime.py``, ``ruby_manifests.py``, ``ruby_lockfile.py``,
``ruby_validator.py``).

Every helper here only *builds* argv lists and inspects the filesystem -- no
subprocess is ever launched. ``bundler()`` and ``ruby()`` are patched to
control PATH availability without requiring those tools to be installed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from depfix.ecosystems import ruby_lockfile, ruby_manifests, ruby_runtime, ruby_validator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# ruby_runtime: build_ruby_install_argv
# ---------------------------------------------------------------------------


def test_build_ruby_install_argv_returns_none_when_bundler_missing(tmp_path: Path) -> None:
    with patch.object(ruby_runtime, "bundler", return_value=None):
        assert ruby_runtime.build_ruby_install_argv(tmp_path) is None


def test_build_ruby_install_argv_includes_frozen_flag_when_lockfile_present(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "Gemfile.lock", "GEM\n  remote: https://rubygems.org/\n")
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        argv = ruby_runtime.build_ruby_install_argv(tmp_path)
    assert argv is not None
    assert "--frozen" in argv
    assert "--path" in argv
    assert ruby_runtime.BUNDLE_PATH in argv


def test_build_ruby_install_argv_omits_frozen_flag_when_no_lockfile(tmp_path: Path) -> None:
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        argv = ruby_runtime.build_ruby_install_argv(tmp_path)
    assert argv is not None
    assert "--frozen" not in argv


def test_build_ruby_install_argv_omits_frozen_flag_when_frozen_false(tmp_path: Path) -> None:
    _write(tmp_path / "Gemfile.lock", "GEM\n")
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        argv = ruby_runtime.build_ruby_install_argv(tmp_path, frozen=False)
    assert argv is not None
    assert "--frozen" not in argv


# ---------------------------------------------------------------------------
# ruby_runtime: test_argv
# ---------------------------------------------------------------------------


def test_test_argv_returns_none_when_bundler_missing(tmp_path: Path) -> None:
    _write(tmp_path / ".rspec", "")
    with patch.object(ruby_runtime, "bundler", return_value=None):
        assert ruby_runtime.test_argv(tmp_path) is None


def test_test_argv_returns_rspec_argv_when_rspec_file_present(tmp_path: Path) -> None:
    _write(tmp_path / ".rspec", "")
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        argv = ruby_runtime.test_argv(tmp_path)
    assert argv == ["bundle", "exec", "rspec", "--format", "json"]


def test_test_argv_returns_rspec_argv_when_spec_dir_present(tmp_path: Path) -> None:
    (tmp_path / "spec").mkdir()
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        argv = ruby_runtime.test_argv(tmp_path)
    assert argv == ["bundle", "exec", "rspec", "--format", "json"]


def test_test_argv_returns_rake_test_when_only_minitest_present(tmp_path: Path) -> None:
    test_dir = tmp_path / "test"
    _write(test_dir / "test_app.rb", "")
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        argv = ruby_runtime.test_argv(tmp_path)
    assert argv == ["bundle", "exec", "rake", "test"]


def test_test_argv_prefers_rspec_over_minitest(tmp_path: Path) -> None:
    _write(tmp_path / ".rspec", "")
    test_dir = tmp_path / "test"
    _write(test_dir / "test_app.rb", "")
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        argv = ruby_runtime.test_argv(tmp_path)
    assert argv is not None
    assert "rspec" in argv


def test_test_argv_returns_none_when_no_test_setup(tmp_path: Path) -> None:
    with patch.object(ruby_runtime, "bundler", return_value="/usr/bin/bundle"):
        assert ruby_runtime.test_argv(tmp_path) is None


# ---------------------------------------------------------------------------
# ruby_runtime: has_gemfile / has_test_setup
# ---------------------------------------------------------------------------


def test_has_gemfile_true_when_gemfile_present(tmp_path: Path) -> None:
    _write(tmp_path / "Gemfile", "source 'https://rubygems.org'\n")
    assert ruby_runtime.has_gemfile(tmp_path) is True


def test_has_gemfile_false_when_no_gemfile(tmp_path: Path) -> None:
    assert ruby_runtime.has_gemfile(tmp_path) is False


def test_has_test_setup_true_for_rspec(tmp_path: Path) -> None:
    _write(tmp_path / ".rspec", "")
    assert ruby_runtime.has_test_setup(tmp_path) is True


def test_has_test_setup_true_for_minitest(tmp_path: Path) -> None:
    test_dir = tmp_path / "test"
    _write(test_dir / "test_app.rb", "")
    assert ruby_runtime.has_test_setup(tmp_path) is True


def test_has_test_setup_false_for_empty_checkout(tmp_path: Path) -> None:
    assert ruby_runtime.has_test_setup(tmp_path) is False


# ---------------------------------------------------------------------------
# ruby_manifests: _iter_gemfiles skips .depfix-bundle
# ---------------------------------------------------------------------------


def test_iter_gemfiles_skips_depfix_bundle_directory(tmp_path: Path) -> None:
    _write(tmp_path / "Gemfile", "source 'https://rubygems.org'\n")
    _write(tmp_path / ".depfix-bundle" / "gems" / "rack-3.0.0" / "Gemfile", "")

    found = ruby_manifests._iter_gemfiles(tmp_path)
    paths = [p.relative_to(tmp_path).as_posix() for p in found]

    assert "Gemfile" in paths
    assert not any(".depfix-bundle" in p for p in paths)


def test_iter_gemfiles_skips_vendor_directory(tmp_path: Path) -> None:
    _write(tmp_path / "Gemfile", "source 'https://rubygems.org'\n")
    _write(tmp_path / "vendor" / "bundle" / "Gemfile", "")

    found = ruby_manifests._iter_gemfiles(tmp_path)
    paths = [p.relative_to(tmp_path).as_posix() for p in found]

    assert "Gemfile" in paths
    assert not any("vendor" in p for p in paths)


def test_iter_gemfiles_does_not_include_gemspec_files(tmp_path: Path) -> None:
    _write(tmp_path / "Gemfile", "source 'https://rubygems.org'\n")
    _write(tmp_path / "my_gem.gemspec", "Gem::Specification.new {|s| s.name = 'my_gem' }\n")

    found = ruby_manifests._iter_gemfiles(tmp_path)
    names = [p.name for p in found]

    assert "my_gem.gemspec" not in names
    assert "Gemfile" in names


# ---------------------------------------------------------------------------
# ruby_lockfile: ruby_lockfile_paths excludes .depfix-bundle
# ---------------------------------------------------------------------------


def test_ruby_lockfile_paths_excludes_depfix_bundle(tmp_path: Path) -> None:
    _write(tmp_path / "Gemfile.lock", "GEM\n")
    _write(tmp_path / ".depfix-bundle" / "gems" / "rack-3.0.0" / "Gemfile.lock", "GEM\n")

    paths = ruby_lockfile.ruby_lockfile_paths(tmp_path)
    relpaths = [p.relative_to(tmp_path).as_posix() for p in paths]

    assert "Gemfile.lock" in relpaths
    assert not any(".depfix-bundle" in p for p in relpaths)


def test_ruby_lockfile_paths_excludes_vendor(tmp_path: Path) -> None:
    _write(tmp_path / "Gemfile.lock", "GEM\n")
    _write(tmp_path / "vendor" / "bundle" / "Gemfile.lock", "GEM\n")

    paths = ruby_lockfile.ruby_lockfile_paths(tmp_path)
    relpaths = [p.relative_to(tmp_path).as_posix() for p in paths]

    assert "Gemfile.lock" in relpaths
    assert not any("vendor" in p for p in relpaths)


# ---------------------------------------------------------------------------
# ruby_validator: safe skip when ruby not on PATH
# ---------------------------------------------------------------------------


def test_validate_ruby_syntax_returns_true_when_ruby_not_on_path(tmp_path: Path) -> None:
    rb_file = _write(tmp_path / "app.rb", "puts 'hello'\n")
    with patch("depfix.ecosystems.ruby_validator.shutil.which", return_value=None):
        ok, msg = ruby_validator.validate_ruby_syntax(rb_file)
    assert ok is True
    assert "PATH" in msg
