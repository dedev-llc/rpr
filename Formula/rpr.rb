class Rpr < Formula
  include Language::Python::Virtualenv

  desc "Stealth PR reviewer — looks like you wrote every word"
  homepage "https://github.com/dedev-llc/rpr"
  # TODO: After the first PyPI publish, replace these with the real values.
  # Homebrew rejects the /source/r/rpr/ shortcut URL — you must use the
  # canonical hashed URL shown on https://pypi.org/project/rpr/#files
  # under the "Source Distribution" row.
  #
  #   1. Visit https://pypi.org/project/rpr/0.1.0/#files
  #   2. Right-click "rpr-0.1.0.tar.gz" → Copy Link → paste below as `url`
  #   3. Run: brew fetch --build-from-source Formula/rpr.rb
  #      (or: curl -sL <that-url> | shasum -a 256)
  #   4. Paste the sha256 below
  url "https://files.pythonhosted.org/packages/source/r/rpr/rpr-0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"

  depends_on "gh"
  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage: rpr", shell_output("#{bin}/rpr --help")
  end
end
