import importlib
import os
import inspect
from typing import List, Tuple
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def get_strategy_classes(strategy_dir: str = "strategy") -> List[Tuple[str, str]]:
    """
    掃描 strategy 資料夾，回傳 (class_name, strategy_name) 清單。
    """
    result = []
    for fname in os.listdir(strategy_dir):
        if fname.endswith(".py") and not fname.startswith("__"):
            module_name = fname[:-3]
            module = importlib.import_module(f"{strategy_dir}.{module_name}")
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if hasattr(obj, "strategy_name") or hasattr(obj(), "strategy_name"):
                    # 取得 strategy_name 屬性
                    try:
                        strategy_name = getattr(obj, "strategy_name", None) or getattr(obj(), "strategy_name", None)
                        result.append((name, strategy_name))
                    except Exception:
                        continue
    return result

if __name__ == "__main__":
    print(get_strategy_classes())
