"use client";

export function Avatar({
  name,
  avatarUrl,
  size = 36,
}: {
  name: string;
  avatarUrl?: string | null;
  size?: number;
}) {
  if (avatarUrl) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={avatarUrl}
        alt={name}
        className="avatar"
        style={{ width: size, height: size }}
      />
    );
  }
  const initial = name.trim().slice(0, 1).toUpperCase() || "?";
  return (
    <div className="avatar avatar-fallback" style={{ width: size, height: size }}>
      {initial}
    </div>
  );
}
