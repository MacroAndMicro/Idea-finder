"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

type Props = { href: string; match: string[]; children: React.ReactNode };

const base = "inline-flex min-h-11 items-center rounded px-3 text-sm font-medium underline-offset-4 hover:underline";

function isCurrent(path: string, match: string[]): boolean {
  return match.some((m) => (m === "/" ? path === "/" : path === m || path.startsWith(`${m}/`)));
}

function ActiveLink({ href, match, children }: Props) {
  const current = isCurrent(usePathname(), match);
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={`${base} ${current ? "text-accent underline" : "text-muted hover:text-foreground"}`}
    >
      {children}
    </Link>
  );
}

/**
 * Primary nav link that marks itself current for its own section (e.g. "/" also covers /cards/*).
 * The pathname is request-time data on dynamic routes, so it streams in; the fallback is the same
 * link without the current-page state.
 */
export default function NavLink(props: Props) {
  return (
    <Suspense
      fallback={
        <Link href={props.href} className={`${base} text-muted hover:text-foreground`}>
          {props.children}
        </Link>
      }
    >
      <ActiveLink {...props} />
    </Suspense>
  );
}
