{
  description = "hello world application using uv2nix";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
        in
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope
          (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.wheel
              overlay
            ]
          )
      );

    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope editableOverlay;
          virtualenv = pythonSet.mkVirtualEnv "hello-world-dev-env" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [
              virtualenv
              pkgs.uv
              pkgs.nodejs
              pkgs.minizinc
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };
            shellHook = ''
              alias claude="npx -y @anthropic-ai/claude-code -- --dangerously-skip-permissions"
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
              . ${virtualenv}/bin/activate
            '';
          };
        }
      );

      packages = forAllSystems (system: {
        default = pythonSets.${system}.mkVirtualEnv "hello-world-env" workspace.deps.default;
      });

      apps = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope editableOverlay;
          virtualenv = pythonSet.mkVirtualEnv "hello-world-dev-env" workspace.deps.all;
        in
        {
          default = {
            type = "app";
            program = toString (pkgs.writeShellScript "run-chat-app" ''
              export PATH="${virtualenv}/bin:${pkgs.uv}/bin:${pkgs.minizinc}/bin:${pkgs.steam-run}/bin:$PATH"
              export UV_NO_SYNC=1
              export UV_PYTHON=${pythonSet.python.interpreter}
              export UV_PYTHON_DOWNLOADS=never
              export REPO_ROOT=$(pwd)
              export PYTHONPATH="${virtualenv}/${pythonSet.python.sitePackages}"
              cd "$REPO_ROOT"
              ${pkgs.steam-run}/bin/steam-run ${pythonSet.python.interpreter} src/app
            '');
          };
        }
      );
    };
}
