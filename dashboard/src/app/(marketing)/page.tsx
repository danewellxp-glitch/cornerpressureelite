import { Hero } from "./components/Hero";
import { Manifesto } from "./components/Manifesto";
import { Pillars } from "./components/Pillars";
import { HowItWorks } from "./components/HowItWorks";
import { Pricing } from "./components/Pricing";
import { FAQ } from "./components/FAQ";
import { CTAFinal } from "./components/CTAFinal";

export default function LandingPage() {
  return (
    <>
      <Hero />
      <Manifesto />
      <Pillars />
      <HowItWorks />
      <Pricing />
      <FAQ />
      <CTAFinal />
    </>
  );
}
