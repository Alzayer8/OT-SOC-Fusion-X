interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = "Loading application foundation" }: LoadingStateProps) {
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <span className="loading-indicator" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}
