{
  description = "Chat App with FastAPI";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python311;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python
            uv
            git
          ];

          shellHook = ''
            echo "Chat App development environment"
            echo "Python version: $(python --version)"
            echo "uv version: $(uv --version)"
            echo ""
            echo "To install dependencies: uv sync"
            echo "To run the app: uv run python -m chat_app"
          '';
        };
      });
}