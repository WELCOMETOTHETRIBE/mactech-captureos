import { SignIn } from "@clerk/nextjs";

export default function Page() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4">
      <SignIn />
    </div>
  );
}
