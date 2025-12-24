# HintzeToolShare v0.9.9 Release Notes

## [v0.9.9] - 2025-12-24
### Added
- **AI Return Assistant**: A new AI-powered interface in the "Return Tools" tab allows users to naturally describe returns (e.g., "I returned the drill to Shawn") and have the actions processed automatically.
- **Bulk Returns**: Multi-selection capability added to the "Return Tools" tables, enabling users to return or mark received multiple items at once.
- **Persistent View Toggle**: New "Borrowed" vs "Lent" toggle in the Return Center that remembers your view preference.

### Changed
- **Repository Restructuring**: Major code reorganization. Moved core logic to `core/`, scripts to `scripts/`, and data to `data/` for better maintainability.
- **UI Visuals**:
    - Replaced transient toast notifications with high-visibility success banners.
    - Improved column layout and centering in the Return Center.


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
