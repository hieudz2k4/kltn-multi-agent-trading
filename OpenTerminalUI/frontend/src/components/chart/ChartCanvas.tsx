import { forwardRef } from "react";

type Props = {
  className?: string;
};

export const ChartCanvas = forwardRef<HTMLDivElement, Props>(function ChartCanvas(
  { className = "h-full w-full" },
  ref,
) {
  return <div ref={ref} className={className} aria-hidden="true" />;
});
