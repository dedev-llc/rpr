# Review Guidelines

These are injected into every review to enforce team standards.
Edit this file to match your project's conventions.

## Architecture
- We use Clean Architecture with BLoC pattern
- Feature-first folder structure: lib/features/<feature>/{data,domain,presentation}
- Repository pattern for data layer — no direct API calls from BLoC
- Use cases should be single-responsibility

## Dart / Flutter
- Prefer `final` over `var` wherever possible
- Use `sealed` classes for state modeling
- Freezed unions for complex states, simple classes for straightforward ones
- No business logic in widgets — everything through BLoC
- Dispose streams and controllers properly
- Handle all error states — no silent failures
- Use `Either<Failure, Success>` pattern for repository returns

## State Management
- BLoC for feature-level state
- No nested BlocBuilders unless absolutely necessary
- Use BlocSelector for granular rebuilds
- Events should be past-tense verbs (e.g., `LoginSubmitted`, `UserProfileLoaded`)

## API & Networking
- All API calls must have proper error handling with timeout
- Use interceptors for auth token refresh
- DTOs for API responses, separate domain models for business logic
- Never expose raw API models to the presentation layer

## Security
- No hardcoded API keys or secrets
- Validate all user input
- Sanitize data before rendering in WebViews
- Use secure storage for tokens

## Performance
- Avoid unnecessary rebuilds (const constructors, proper keys)
- Lazy loading for lists and heavy content
- Image caching and proper sizing
- No synchronous heavy computation on main isolate
