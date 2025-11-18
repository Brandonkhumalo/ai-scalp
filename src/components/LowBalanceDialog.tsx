import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertCircle, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface LowBalanceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentBalance: number;
}

export const LowBalanceDialog = ({ open, onOpenChange, currentBalance }: LowBalanceDialogProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md border-destructive/20">
        <button
          onClick={() => onOpenChange(false)}
          className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </button>
        
        <DialogHeader className="space-y-4">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="h-8 w-8 text-destructive" />
          </div>
          <DialogTitle className="text-center text-2xl">
            Insufficient Balance
          </DialogTitle>
          <DialogDescription className="text-center text-base">
            Your current Alpaca account balance is <span className="font-semibold text-foreground">${currentBalance.toFixed(2)}</span>.
            <br />
            You need at least <span className="font-semibold text-foreground">$5.00</span> to start AI trading.
            <br />
            <br />
            <span className="text-sm text-muted-foreground">
              Please ensure your Alpaca paper trading account has sufficient virtual funds to continue.
            </span>
          </DialogDescription>
        </DialogHeader>
        
        <DialogFooter className="sm:justify-center mt-4">
          <Button
            onClick={() => onOpenChange(false)}
            className="w-full sm:w-auto"
            variant="outline"
            size="lg"
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
