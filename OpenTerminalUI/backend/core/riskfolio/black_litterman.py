import numpy as np

def bl_implied_returns(cov: np.ndarray, w_market: np.ndarray, risk_aversion: float = 2.0) -> np.ndarray:
    """
    Compute implied equilibrium returns (Pi).
    Pi = delta * cov * w_mkt
    """
    return risk_aversion * (cov @ w_market)

def bl_posterior_returns(cov, w_market, P, Q, *, risk_aversion=2.0, tau=0.05, omega=None) -> tuple[np.ndarray, np.ndarray]:
    """
    Black-Litterman posterior returns and covariance.
    """
    n = len(w_market)
    Pi = bl_implied_returns(cov, w_market, risk_aversion)
    
    if P is None or len(P) == 0:
        return Pi, cov
    
    P = np.array(P)
    Q = np.array(Q).reshape(-1, 1)
    Pi = Pi.reshape(-1, 1)
    
    # If omega is None, omega = diag(P @ (tau*cov) @ P.T)
    if omega is None:
        omega = np.diag(np.diag(P @ (tau * cov) @ P.T))
    
    # Standard BL formula
    # mu_bl = [ (tau*cov)^-1 + P' * omega^-1 * P ]^-1 * [ (tau*cov)^-1 * Pi + P' * omega^-1 * Q ]
    
    tau_cov_inv = np.linalg.pinv(tau * cov)
    omega_inv = np.linalg.pinv(omega)
    
    M = np.linalg.pinv(tau_cov_inv + P.T @ omega_inv @ P)
    mu_bl = M @ (tau_cov_inv @ Pi + P.T @ omega_inv @ Q)
    
    # posterior_cov = cov + M
    # Note: Some versions use different formulas for posterior_cov. 
    # The prompt says: posterior_cov = cov + inv( inv(tau*cov) + P.T @ inv(omega) @ P )
    posterior_cov = cov + M
    
    return mu_bl.flatten(), posterior_cov
