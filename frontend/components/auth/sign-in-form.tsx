"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

interface SignInFormProps {
  onSubmit?: (data: { email: string; password: string }) => void;
}

export function SignInForm({ onSubmit }: SignInFormProps) {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [agreeTerms, setAgreeTerms] = React.useState(false);
  const [subscribeNewsletter, setSubscribeNewsletter] = React.useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit?.({ email, password });
  };

  return (
    <div className="w-full max-w-md space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold">Sign In</h1>
        <p className="text-muted-foreground">
          Enter your email and password to Sign In.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Your email</Label>
          <Input
            id="email"
            type="email"
            placeholder="name@mail.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="********"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <div className="flex items-center space-x-2">
          <Checkbox
            id="terms"
            checked={agreeTerms}
            onCheckedChange={(checked) => setAgreeTerms(checked as boolean)}
          />
          <label
            htmlFor="terms"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            I agree the{" "}
            <Link href="#" className="text-primary underline">
              Terms and Conditions
            </Link>
          </label>
        </div>

        <Button type="submit" className="w-full">
          Sign In
        </Button>

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="newsletter"
              checked={subscribeNewsletter}
              onCheckedChange={(checked) =>
                setSubscribeNewsletter(checked as boolean)
              }
            />
            <label
              htmlFor="newsletter"
              className="text-sm font-medium leading-none"
            >
              Subscribe me to newsletter
            </label>
          </div>
          <Link
            href="#"
            className="text-sm font-medium text-muted-foreground hover:underline"
          >
            Forgot Password
          </Link>
        </div>

        <div className="space-y-3">
          <Button variant="outline" type="button" className="w-full gap-2">
            <Image
              src="/images/google.svg"
              alt="Google"
              width={20}
              height={20}
            />
            Sign in With Google
          </Button>
          <Button variant="outline" type="button" className="w-full gap-2">
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
            </svg>
            Sign in With Twitter
          </Button>
        </div>

        <p className="text-center text-sm text-muted-foreground">
          Not registered?{" "}
          <Link
            href="/auth/sign-up"
            className="font-medium text-foreground hover:underline"
          >
            Create account
          </Link>
        </p>
      </form>
    </div>
  );
}
