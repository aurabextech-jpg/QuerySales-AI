/** Card component — glass-card style container. */

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg";
}

const paddingMap = { sm: "p-4", md: "p-6", lg: "p-8" };

export function Card({ children, className = "", padding = "md" }: CardProps) {
  return (
    <div className={`glass-card ${paddingMap[padding]} ${className}`}>
      {children}
    </div>
  );
}
