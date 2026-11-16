type P = { className?: string };
const base = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export const CrossIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" />
  </svg>
);
export const LockIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);
export const CheckIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <path d="m5 12 5 5 9-10" />
  </svg>
);
export const ShieldIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z" />
    <path d="M9.5 9.5l5 5M14.5 9.5l-5 5" />
  </svg>
);
export const DocIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
    <path d="M14 3v6h6" />
  </svg>
);
export const DbIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
    <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
  </svg>
);
export const SendIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />
  </svg>
);
export const LogoutIcon = ({ className }: P) => (
  <svg viewBox="0 0 24 24" className={className} {...base}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
  </svg>
);
