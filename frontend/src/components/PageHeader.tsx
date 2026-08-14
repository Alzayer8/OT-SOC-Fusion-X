interface PageHeaderProps {
  title: string;
  description: string;
}

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header className="page-header">
      <p className="page-header__eyebrow">OT-SOC Fusion X</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
