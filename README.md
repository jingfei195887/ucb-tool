# ucb-tool

GUI + CLI editor for Infineon AURIX TC4Dx / TC48x / TC4Zx UCB hex files.

## Install (development)

```
git clone <repo>
cd ucb-tool
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```
ucbtool-gui              # launch GUI
ucbtool show ucb.hex --chip tc4d9   # dump all UCBs to console
```

See `docs/user_guide.md` for full reference.
