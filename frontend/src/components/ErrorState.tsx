interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "This view could not be displayed",
  description = "The application returned a safe error. No operational action was taken.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="state state--error" role="alert">
      <span className="state__symbol" aria-hidden="true">
        !
      </span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
        {onRetry ? (
          <button className="button" type="button" onClick={onRetry}>
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}
