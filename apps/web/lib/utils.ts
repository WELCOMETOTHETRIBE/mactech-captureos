import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Standard shadcn-shape class merger. `cn(...inputs)` runs `clsx` first to
 * filter falsy values + flatten conditionals, then `tailwind-merge` resolves
 * conflicting Tailwind classes (later wins). Used by every primitive in
 * `components/ui/`.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
