"""The heart of tinyrepo — everything routes through the Engine."""


class Engine:
    """Central dispatcher. Widely referenced across the package."""

    def __init__(self, config):
        self.config = config

    def run_pipeline(self, task):
        plan = self.make_plan(task)
        return self.execute(plan)

    def make_plan(self, task):
        return {"task": task, "steps": ["a", "b"]}

    def execute(self, plan):
        return len(plan["steps"])


def create_engine(config):
    return Engine(config)
