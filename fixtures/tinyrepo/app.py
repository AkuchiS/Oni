"""Entrypoint — builds an Engine and drives run_pipeline."""
from core.engine import create_engine, Engine


def main():
    engine = create_engine({"debug": True})
    result = engine.run_pipeline("hello")
    another = Engine({}).run_pipeline("world")
    return result + another


if __name__ == "__main__":
    print(main())
