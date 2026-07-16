---
name: concise-code
description: >
  Keep generated code concise, minimal, and free of unnecessary verbosity. Use this skill
  whenever writing, editing, or reviewing code — especially when generating scripts, functions,
  components, or any code output. Trigger on any coding task to avoid over-engineered, bloated,
  or overly commented output. Also use when the user complains that code is "too long", "verbose",
  "too many comments", "unnecessary boilerplate", or asks to "simplify", "clean up", or "trim" code.
---

# Concise Code

Code output should be minimal, readable, and purposeful. Every line must earn its place.

## Core Rules

**No unnecessary comments**
- Omit comments that restate what the code already says
- No block comments above every function unless the logic is genuinely non-obvious
- No section dividers like `# --- Setup ---` or `# === Main ===`

**No boilerplate padding**
- No blank `__init__` methods unless needed
- No `pass` statements except where syntactically required
- No redundant type hints that mirror obvious variable names
- No default argument repetition when defaults are implicit

**No over-engineering**
- Don't abstract into helper functions unless the logic is reused 2+ times
- Don't add error handling for cases outside the stated scope
- Don't add logging, metrics, or config loading unless asked

**No verbose naming**
- Prefer `fn`, `cb`, `res`, `err` over `callbackFunction`, `responseObject`, `errorMessage` in short-lived scopes
- Avoid tautological names: `userObject`, `dataList`, `configSettings`

**No defensive padding**
- No `TODO` comments unless the user asked for a scaffold
- No `raise NotImplementedError` stubs in working code
- No `print("Starting...")` / `print("Done.")` debug breadcrumbs

## What Good Looks Like

**Too verbose:**
```python
def calculate_area(width: int, height: int) -> int:
    """
    Calculate the area of a rectangle.
    
    Args:
        width: The width of the rectangle.
        height: The height of the rectangle.
    
    Returns:
        The area as an integer.
    """
    # Multiply width by height to get area
    area = width * height
    return area
```

**Concise:**
```python
def area(w, h):
    return w * h
```

---

**Too verbose:**
```javascript
// Function to fetch user data from the API
async function fetchUserData(userId) {
  try {
    // Make the API request
    const response = await fetch(`/api/users/${userId}`);
    // Parse the JSON response
    const data = await response.json();
    // Return the data
    return data;
  } catch (error) {
    // Log the error to the console
    console.error('Error fetching user:', error);
  }
}
```

**Concise:**
```javascript
async function fetchUser(id) {
  const res = await fetch(`/api/users/${id}`);
  return res.json();
}
```

## When More Is OK

- Public library APIs: include docstrings for exported symbols
- Complex algorithms: one comment explaining *why*, not *what*
- Security-sensitive logic: comment the invariant being enforced
- User explicitly asks for verbose/documented output

## Checklist Before Outputting Code

- [ ] Can any comment be deleted without losing meaning?
- [ ] Can any variable be inlined?
- [ ] Can any function be collapsed into its caller?
- [ ] Are there any `print`, `TODO`, or stub lines the user didn't ask for?
- [ ] Does every parameter name add information beyond its type?

If yes to any — trim it.
