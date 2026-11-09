import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
import scipy.spatial.distance as ssd

def hrp_weights(returns, linkage_method: str = "ward", risk_measure: str = "MV") -> dict[str, float]:
    """
    Hierarchical Risk Parity (López de Prado) using scipy clustering.
    """
    if returns.shape[1] < 3:
        # Fallback to inverse variance
        cov = returns.cov()
        ivp = 1.0 / np.diag(cov)
        ivp /= ivp.sum()
        return {sym: round(float(ivp[i]), 6) for i, sym in enumerate(returns.columns)}

    corr = returns.corr().fillna(0)
    cov = returns.cov().fillna(0)
    
    # Distance matrix
    dist = np.sqrt(np.clip((1.0 - corr.values) / 2.0, 0, 1))
    
    # Linkage
    # squareform requires a symmetric matrix with zero diagonal
    np.fill_diagonal(dist, 0)
    condensed = ssd.squareform(dist, checks=False)
    link = sch.linkage(condensed, method=linkage_method)
    
    # Quasi-diagonalization
    sort_ix = sch.leaves_list(link)
    sorted_items = returns.columns[sort_ix].tolist()
    
    # Recursive bisection
    weights = pd.Series(1.0, index=sorted_items)
    cluster_items = [sorted_items]
    
    while len(cluster_items) > 0:
        cluster_items = [c[i:j] for c in cluster_items for i, j in ((0, len(c) // 2), (len(c) // 2, len(c))) if len(c) > 1]
        
        for i in range(0, len(cluster_items), 2):
            c_left = cluster_items[i]
            c_right = cluster_items[i+1]
            
            v_left = _get_cluster_var(cov, c_left)
            v_right = _get_cluster_var(cov, c_right)
            
            alpha = 1.0 - v_left / (v_left + v_right)
            weights[c_left] *= alpha
            weights[c_right] *= (1.0 - alpha)
            
    return {sym: round(float(weights[sym]), 6) for sym in returns.columns}

def _get_cluster_var(cov, cluster_items):
    cov_c = cov.loc[cluster_items, cluster_items]
    ivp = 1.0 / np.diag(cov_c)
    ivp /= ivp.sum()
    w = ivp.reshape(-1, 1)
    return np.dot(np.dot(w.T, cov_c), w)[0, 0]
