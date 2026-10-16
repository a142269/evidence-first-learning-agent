"""
Deep Knowledge Tracing (DKT) — Piech et al. 2015

PyTorch implementation of the seminal DKT model:
- Input at each timestep: 2*n_skills one-hot encoding
    (first n_skills for correct+skill, last n_skills for wrong+skill)
- Architecture: LSTM → fully-connected → sigmoid
- Output: probability of answering correctly for each skill at next timestep
- Loss: masked BCE — only compute loss on the skill practiced at that step

References:
    - Piech, C., Bassen, J., Huang, J., et al. (2015).
      "Deep Knowledge Tracing." NIPS 2015.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

logger = logging.getLogger(__name__)


class DKTModel(nn.Module):
    """Deep Knowledge Tracing LSTM model.

    Args:
        n_skills: Number of knowledge components (skills).
        hidden_dim: LSTM hidden dimension.
        n_layers: Number of LSTM layers.
        dropout: Dropout probability.
    """

    def __init__(
        self,
        n_skills: int,
        hidden_dim: int = 64,
        n_layers: int = 1,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.n_skills = n_skills
        self.hidden_dim = hidden_dim
        self.input_dim = 2 * n_skills  # correct+skill_onehot | wrong+skill_onehot

        self.lstm = nn.LSTM(
            input_size=self.input_dim,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0,
        )
        self.fc = nn.Linear(hidden_dim, n_skills)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: (batch, seq_len, 2 * n_skills) input tensor.

        Returns:
            (batch, seq_len, n_skills) predicted probabilities per skill.
        """
        lstm_out, _ = self.lstm(x)
        lstm_out = self.dropout(lstm_out)
        logits = self.fc(lstm_out)
        return torch.sigmoid(logits)


class DKTDataset(Dataset):
    """Dataset wrapper for DKT training (Piech 2015 standard encoding).

    Input encoding (2*n_skills dim):
        - If correct: skill_onehot in [0:n_skills], zeros in [n_skills:2*n_skills]
        - If wrong:   zeros in [0:n_skills], skill_onehot in [n_skills:2*n_skills]

    Target encoding (n_skills dim) + mask (n_skills dim):
        - target[skill_idx] = correct (0 or 1)
        - mask[skill_idx] = 1 (only this position contributes to loss)
    """

    def __init__(
        self,
        sequences: List[List[dict]],
        max_seq_len: Optional[int] = None,
    ):
        self.inputs: List[np.ndarray] = []
        self.targets: List[np.ndarray] = []
        self.masks: List[np.ndarray] = []

        if max_seq_len is None and sequences:
            max_seq_len = max(len(s) for s in sequences if s)
        self.max_seq_len = max_seq_len or 200

        for seq in sequences:
            if not seq:
                continue
            n_skills = seq[0]["skill_onehot"].shape[0]
            # Input: (max_seq_len, 2*n_skills)
            input_seq = np.zeros((self.max_seq_len, 2 * n_skills), dtype=np.float32)
            # Target: (max_seq_len, n_skills) — correctness at practiced skill
            target_seq = np.zeros((self.max_seq_len, n_skills), dtype=np.float32)
            # Mask: (max_seq_len, n_skills) — 1 where we have a label
            mask_seq = np.zeros((self.max_seq_len, n_skills), dtype=np.float32)

            for t in range(min(len(seq), self.max_seq_len)):
                entry = seq[t]
                skill_oh = entry["skill_onehot"].astype(np.float32)
                correct = int(entry["correct"])
                skill_idx = int(np.argmax(skill_oh))

                # Piech encoding: correct → first half, wrong → second half
                if correct == 1:
                    input_seq[t, :n_skills] = skill_oh
                else:
                    input_seq[t, n_skills:] = skill_oh

                # Target for NEXT step prediction: we predict at step t the
                # probability of answering the skill at step t correctly.
                # Standard DKT: input[0..t-1] predicts target[t].
                # So we shift: input_seq[t] is built from seq[t], and it
                # predicts target at t+1. We store target at position t
                # to be predicted from inputs up to t-1.
                # Simplification: target[t] = correctness of seq[t],
                # mask[t] = 1 at practiced skill. The model sees inputs[0..t-1]
                # and predicts target[t]. We handle the shift in the training
                # loop by feeding inputs[:-1] and comparing to targets[1:].
                target_seq[t, skill_idx] = float(correct)
                mask_seq[t, skill_idx] = 1.0

            self.inputs.append(input_seq)
            self.targets.append(target_seq)
            self.masks.append(mask_seq)

        self.n_skills = sequences[0][0]["skill_onehot"].shape[0] if sequences and sequences[0] else 1

    def __len__(self) -> int:
        return len(self.inputs)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return (
            torch.from_numpy(self.inputs[idx]),
            torch.from_numpy(self.targets[idx]),
            torch.from_numpy(self.masks[idx]),
        )


class DKTTrainer:
    """Training loop for DKT with masked BCE loss.

    Args:
        n_skills: Number of skills.
        hidden_dim: LSTM hidden dimension.
        n_layers: Number of LSTM layers.
        learning_rate: Adam learning rate.
        batch_size: Training batch size.
        max_epochs: Maximum training epochs.
        patience: Early stopping patience.
        device: torch device string.
    """

    def __init__(
        self,
        n_skills: int,
        hidden_dim: int = 64,
        n_layers: int = 1,
        learning_rate: float = 0.001,
        batch_size: int = 32,
        max_epochs: int = 30,
        patience: int = 5,
        device: Optional[str] = None,
    ):
        self.n_skills = n_skills
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.lr = learning_rate
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.model = DKTModel(
            n_skills=n_skills,
            hidden_dim=hidden_dim,
            n_layers=n_layers,
        ).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.BCELoss(reduction="none")

    def _masked_loss(
        self, outputs: torch.Tensor, targets: torch.Tensor, masks: torch.Tensor
    ) -> torch.Tensor:
        """Masked BCE loss — only compute on practiced skill positions."""
        loss = self.criterion(outputs, targets)  # (batch, seq, n_skills)
        masked = loss * masks  # zero out non-practiced positions
        total = masked.sum()
        count = masks.sum().clamp(min=1.0)
        return total / count

    def train_model(
        self,
        train_sequences: List[List[dict]],
        val_sequences: Optional[List[List[dict]]] = None,
    ) -> dict:
        """Train DKT model with shifted input/target and masked loss.

        DKT protocol: inputs[t] (interaction at step t) is used to predict
        target[t+1] (correctness at step t+1). We feed inputs[:-1] and
        compare against targets[1:] with masks[1:].
        """
        train_dataset = DKTDataset(train_sequences, max_seq_len=200)
        train_loader = DataLoader(
            train_dataset, batch_size=self.batch_size, shuffle=True,
            num_workers=0,  # Windows safe
        )

        best_val_loss = float("inf")
        patience_counter = 0
        best_epoch = 0

        self.model.train()
        for epoch in range(self.max_epochs):
            total_loss = 0.0
            n_batches = 0
            for inputs, targets, masks in train_loader:
                inputs = inputs.to(self.device)
                targets = targets.to(self.device)
                masks = masks.to(self.device)

                # Shift: inputs[0..T-2] predict targets[1..T-1]
                if inputs.size(1) > 1:
                    inp = inputs[:, :-1, :]
                    tgt = targets[:, 1:, :]
                    msk = masks[:, 1:, :]
                else:
                    continue

                self.optimizer.zero_grad()
                outputs = self.model(inp)  # (batch, T-1, n_skills)
                loss = self._masked_loss(outputs, tgt, msk)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=3.0)
                self.optimizer.step()

                total_loss += loss.item()
                n_batches += 1

            avg_loss = total_loss / max(n_batches, 1)

            if val_sequences is not None and len(val_sequences) > 0:
                val_loss = self._eval(val_sequences)
                if val_loss < best_val_loss - 1e-4:
                    best_val_loss = val_loss
                    best_epoch = epoch
                    patience_counter = 0
                else:
                    patience_counter += 1
                if patience_counter >= self.patience:
                    logger.info("[DKT] Early stopping at epoch %d", epoch)
                    break
            else:
                best_epoch = epoch

            if (epoch + 1) % 5 == 0:
                logger.info(
                    "[DKT] Epoch %d/%d — train_loss=%.4f",
                    epoch + 1, self.max_epochs, avg_loss,
                )

        return {
            "epochs_trained": best_epoch + 1,
            "best_val_loss": best_val_loss,
        }

    def _eval(self, sequences: List[List[dict]]) -> float:
        """Evaluate on a set of sequences, return average masked BCE loss."""
        dataset = DKTDataset(sequences, max_seq_len=200)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=False, num_workers=0)
        self.model.eval()
        total_loss = 0.0
        n_batches = 0
        with torch.no_grad():
            for inputs, targets, masks in loader:
                inputs = inputs.to(self.device)
                targets = targets.to(self.device)
                masks = masks.to(self.device)
                if inputs.size(1) > 1:
                    inp = inputs[:, :-1, :]
                    tgt = targets[:, 1:, :]
                    msk = masks[:, 1:, :]
                else:
                    continue
                outputs = self.model(inp)
                loss = self._masked_loss(outputs, tgt, msk)
                total_loss += loss.item()
                n_batches += 1
        self.model.train()
        return total_loss / max(n_batches, 1)

    def predict(
        self,
        sequences: List[List[dict]],
    ) -> List[List[float]]:
        """Predict correctness probabilities for each timestep.

        Uses the DKT next-step protocol: at step t, the model has seen
        interactions 0..t-1 and predicts the probability of answering
        correctly for the skill practiced at step t.

        Args:
            sequences: Per-student interaction sequences.

        Returns:
            List of per-student per-step predicted probabilities for the
            practiced skill at that step.
        """
        self.model.eval()
        all_preds: List[List[float]] = []

        for seq in sequences:
            n = len(seq)
            if n == 0:
                all_preds.append([])
                continue

            # Build input tensor with Piech encoding
            input_tensor = torch.zeros(1, n, 2 * self.n_skills, device=self.device)
            for t, entry in enumerate(seq):
                skill_oh = entry["skill_onehot"].astype(np.float32)
                correct = int(entry["correct"])
                if correct == 1:
                    input_tensor[0, t, :self.n_skills] = torch.from_numpy(skill_oh)
                else:
                    input_tensor[0, t, self.n_skills:] = torch.from_numpy(skill_oh)

            with torch.no_grad():
                output = self.model(input_tensor)  # (1, n, n_skills)

            # Next-step prediction: output[t] predicts step t+1
            # At step 0, no history → use output[0] as prior (or 0.5)
            preds = []
            for t in range(n):
                skill_oh = seq[t]["skill_onehot"]
                skill_idx = int(np.argmax(skill_oh))
                if t == 0:
                    # No history: use model's prior (first output) or 0.5
                    preds.append(float(output[0, 0, skill_idx].cpu()))
                else:
                    # output[t-1] is the prediction made after seeing step t-1,
                    # which predicts step t
                    preds.append(float(output[0, t - 1, skill_idx].cpu()))
            all_preds.append(preds)

        self.model.train()
        return all_preds
