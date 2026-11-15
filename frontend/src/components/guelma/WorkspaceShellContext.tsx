"use client";

import { createContext, useContext } from "react";

/**
 * Shared actions exposed by the unified FieldShift Command Center shell
 * (FieldShiftWorkspaceRoot) to every page rendered inside it — including the
 * Analysis Studio routes (/select-field, /farm-profile, /comparison, /evidence).
 */
export interface WorkspaceShellActions {
  /** Opens the Account & Sync modal (sign in / register / claim guest data). */
  openAuthModal: () => void;
}

const noop = () => {};

export const WorkspaceShellContext = createContext<WorkspaceShellActions>({
  openAuthModal: noop,
});

export function useWorkspaceShell(): WorkspaceShellActions {
  return useContext(WorkspaceShellContext);
}

