class Rpr < Formula
  include Language::Python::Virtualenv

  desc "Stealth PR reviewer — looks like you wrote every word"
  homepage "https://github.com/dedev-llc/rpr"
  # The release workflow auto-rewrites the `url` and `sha256` lines below in
  # the dedev-llc/homebrew-rpr tap on every published version. The values
  # here are a snapshot of the latest release — the canonical formula lives
  # in the tap repo, this copy is a developer reference and seed.
  url "https://files.pythonhosted.org/packages/b4/0b/a46630537b00936ab829b2461eddf417dd6a10ea2df09c51cb3e8f72bfb3/rpr-0.1.1.tar.gz"
  sha256 "9b51ccae628b16c6211128188560143b638c0546e3e3d4d343ee9242928d7867"
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
