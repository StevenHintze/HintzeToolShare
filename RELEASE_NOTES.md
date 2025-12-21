# HintzeToolShare v0.9.8 Release Notes

## 🛠️ Major Architectural Overhaul
This release introduces significant structural improvements to the codebase, enhancing maintainability and reliability without changing the core user experience.

### ✨ Key Changes
- **Modular Views**: The monolithic `app.py` has been split into dedicated view modules located in `views/`. This makes the code easier to navigate and update.
- **AI Configuration**: All AI prompts have been moved to a centralized `prompts.py` file, simplifying prompt engineering and versioning.
- **Testing Suite**: Added a preliminary test suite in `tests/` covering security logic and data handling.

### 🐛 Bug Fixes & Improvements
- Improved separation of concerns between UI and Business Logic.
- Enhanced type safety and code readability in backend helpers.
- Added foundational unit tests to prevent future regressions.

### 📝 Notes for Developers
- Run the app as usual: `streamlit run app.py`
- Run tests: `python -m unittest discover tests`
