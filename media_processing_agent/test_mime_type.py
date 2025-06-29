from vertexai.generative_models import Part

# Test if mime_type is optional
test_uri = "https://example.com/test.jpg"

# Try without mime_type
try:
    part_without_mime = Part.from_uri(uri=test_uri)
    print("✓ Part.from_uri works WITHOUT mime_type!")
    print(f"  Part created: {part_without_mime}")
except TypeError as e:
    print("✗ Part.from_uri requires mime_type")
    print(f"  Error: {e}")

# Check the method signature
import inspect
sig = inspect.signature(Part.from_uri)
print(f"\nMethod signature: {sig}")
for param_name, param in sig.parameters.items():
    print(f"  {param_name}: {param.default if param.default != inspect.Parameter.empty else 'REQUIRED'}")