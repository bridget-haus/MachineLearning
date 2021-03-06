import numpy as np
import math
import pandas as pd

def get_data(filename):

	with open(filename) as f:

		lines = f.readlines()

		grid = []
		for line in lines[2:12]:
			line = line.rstrip()
			line = line.split(' ')
			line = [int(i) for i in line]
			grid.append(line)

		towers = []
		for line in lines[16:20]:
			line = line.rstrip()
			line = line.split(' ')
			line = line[2:]
			line = [int(i) for i in line]
			towers.append(line)

		noisy_distance = []
		for line in lines[24:]:
			line = line.rstrip()
			line = line.split(' ')
			line = [float(i) for i in line]
			noisy_distance.append(line)

	return grid, towers, noisy_distance

def initial_probability(grid):
    '''Calculate probability of robot's initial position in any 1 cell.'''
    valid_cells = {}
    counter = 1
    x = 0
    y = 0
    for row in grid:
        for column in row:
            # if the cell is valid, create a dict where key = 1-87 free spaces and value = (x,y) coordinates
            if column == 1:
                valid_cells[counter] = [x, y]
                counter += 1
                y += 1
            elif column == 0:
                y += 1
        y = 0
        x += 1
        
    # there are 87 valid cells to start. robot has uniform probability of starting in each of them
    #Make a matrix with initial probability for each valid cell
    init_prob = round((1/len(valid_cells)), 5)
        
    I = np.full(len(valid_cells), init_prob)
    return valid_cells, init_prob, I

def get_trans_neighbors(valid_cells, grid):
    '''For each valid cell, get the id and coordinates of its neighbor.
    This structure will be used to populate the trans_matrix.'''
    
    #Use this for looking up neighbor cell id
    validcells_keys = list(valid_cells.keys())
    validcells_vals = list(valid_cells.values())
    
    free_neighbors_outer = {}
    for key in valid_cells.keys():
        
        free_neighbors_inner = {}

        x_prior = valid_cells[key][0]
        y_prior = valid_cells[key][1]

        if x_prior-1 >= 0 and grid[x_prior-1][y_prior]==1: # moving left is available
            nb_id = validcells_keys[validcells_vals.index([x_prior-1, y_prior])]
            free_neighbors_inner[nb_id] = [x_prior-1, y_prior]
        if x_prior+1 <= 9 and grid[x_prior+1][y_prior]==1: # moving right is available
            nb_id = validcells_keys[validcells_vals.index([x_prior+1, y_prior])]
            free_neighbors_inner[nb_id] = [x_prior+1, y_prior]
        if y_prior-1 >= 0 and grid[x_prior][y_prior-1]==1: # moving down is available
            nb_id = validcells_keys[validcells_vals.index([x_prior, y_prior-1])]
            free_neighbors_inner[nb_id] = [x_prior, y_prior-1]
        if y_prior+1 <= 9 and grid[x_prior][y_prior+1]==1: # moving up is available
            nb_id = validcells_keys[validcells_vals.index([x_prior, y_prior+1])]
            free_neighbors_inner[nb_id] = [x_prior, y_prior+1]

        free_neighbors_outer[key] = free_neighbors_inner
    return free_neighbors_outer

def transition_matrix(free_neighbors, valid_cells):
    '''Create a constant transition matrix, which are probabilities of 
    transitioning to new state conditioned on hidden state.
    Rows - prior valid cells, ascending from 1-87. Row values sum to 1.
    Columns - current valid cells, ascending from 1-87.
    Ex: Row one is for cell coordinates 0,1. Row two is for cell coordinates 0,1... etc.
    '''
    # initialize 87x87 matrix to represent 87 free cells
    trans_matrix = np.zeros((len(valid_cells), len(valid_cells)))
    trans_matrix_index = []
    for i in free_neighbors.keys():
        for j in free_neighbors.keys():
            trans_matrix_index.append(f'{i}|{j}')

    for key_out in free_neighbors.keys():
        vals_outer = free_neighbors[key_out]

        neighbor_count = len(vals_outer.keys())
        prior_prob = round((1 / neighbor_count), 5)
        
        #Fill out the trans matrix, make sure rows sum to 1
        for key_in in vals_outer:
            trans_matrix[key_out -1][key_in-1] = prior_prob
    
    #Flatten the trans matrix into a dictionary
    trans_matrix_flat = dict(enumerate(trans_matrix.flatten(), 1))
    T = {}
    for i, idx in enumerate(trans_matrix_index, 1):
        T[idx] = trans_matrix_flat.get(i)
    return T

def dist_to_tower_range(valid_cells, towers):

    # euclidean distance = sqrt((x2 - x1)^2 + (y2 - y1)^2)

    min_rand_noise = 0.7
    max_rand_noise = 1.3

    dist_tower_range = pd.DataFrame()

    coordinates_list = valid_cells.values()
    dist_tower_range['coordinates'] = coordinates_list
    
    towers_e = enumerate(towers, 1)
    for i, tower in towers_e:
        tower_dists = []
        for cell in coordinates_list:
            dist = math.sqrt((cell[0] - tower[0])**2 + (cell[1] - tower[1])**2)
            # include min and max random noise to generate possible range
            random_noise = [round(dist * min_rand_noise,1), round(dist * max_rand_noise,1)]
            tower_dists.append(random_noise)
        dist_tower_range[i] = tower_dists

    return dist_tower_range

def find_obs_likely_cells(noisy_distance, dist_tower_range, valid_cells):
    '''For each observation distances, find a set of likely cell indexes from the 87 valid cells.
    Use each observation's likely_cells to compute emissions matrix later on.'''
    obs_likely_cells = {}
    for i, obs in enumerate(noisy_distance, 1):
        obs_i = enumerate(obs, 1)

        #Select the coordinates of all valid cells
        tow_coords = dist_tower_range.loc[:, 1]
        tow_indexes = list(tow_coords.index.values)

        #For each observation's tower_dist
        for j, tower_dist in obs_i:
            #find cells that that contain the observation's tower_dist
            tower_matches = {}
            for index, coord in zip(tow_indexes, tow_coords):
                if tower_dist >= coord[0] and tower_dist <= coord[1]:
                    #Save the index and coordinate of the likely cell
                    tower_matches[index] = valid_cells.get(index)

            #When the last tower distances are checked for matches, don't update the tow_coords
            try: 
                tow_coords_next = dist_tower_range.loc[list(tower_matches.keys()), j+1]
            except KeyError:
                break

            #Narrow down the likely tower coordinates, before checking the next tower
            tow_coords = tow_coords_next
            tow_indexes = list(tow_coords.index.values)
        obs_likely_cells[i] = tower_matches
    return obs_likely_cells

def emission_matrices(obs_likely_cells, free_neighbors, valid_cells):
    '''Creates a list of emission matrixes, for each observation.
    Within each emission matrix, Rows represent each likely cell
    Rows - likely cells (i.e. evidence), given the robot's noisy distances from tower. Row values horizontally sum to 1.
    Columns - current valid cells, ascending from 1-87.
    '''
    #Store each observation's emission matrix in a list
    emis_matrix_list = []
    emis_matrix_index_list = []
    
    #Generate emission matrix for each observation
    for obs_index in obs_likely_cells.keys():
        obs = obs_likely_cells.get(obs_index)
        emis_matrix = np.zeros((len(obs), len(valid_cells)))
        
        #Create an index for each emis_matrix
        emis_matrix_index = []        
        for likely_cell in obs.keys():
            for valid_cell in valid_cells.keys():
                emis_matrix_index.append(f'{likely_cell}|{valid_cell}')
                
        emis_matrix_index_list.append(emis_matrix_index)
        
        #For each observation's likely cell
        for i, likely_cell in enumerate(obs.keys()):
            
            #look up likely cell's neighbors
            neighbors = free_neighbors.get(likely_cell)

            #Calculate uniform prob of moving to neighbor
            len_neighbors = len(neighbors.keys())
            prob = 1 / len_neighbors
            #Add the probability to the emissions matrix
            for neighbor in neighbors.keys():
                emis_matrix[i][neighbor-1] = prob
        emis_matrix_list.append(emis_matrix)
    return emis_matrix_list, emis_matrix_index_list

def flatten_emis(emis_matrix_list, emis_matrix_index_list):
    '''Flatten the observation emission matrixes into a list of dicts.'''
    E_list = []
    for emis_m, emis_i in zip(emis_matrix_list, emis_matrix_index_list):
        emis_m_flat = dict(enumerate(emis_m.flatten(), 1))
        E = {}
        for i, idx in enumerate(emis_i, 1):
            E[idx] = emis_m_flat.get(i)
        E_list.append(E)
    return E_list

class robot_stats():
    def __init__(self):
        # read txt file into data structures
        self.grid, self.towers, self.noisy_distance = get_data('hmm-data.txt')

        # probability of robot's initial position in any 1 cell
        self.valid_cells, self.init_prob, self.I = initial_probability(self.grid)

        #Get coordinates of free neighbors for each valid cell
        self.free_neighbors = get_trans_neighbors(self.valid_cells, self.grid)

        # given previous cell, what is conditional probability robot moved to another cell
        self.T = transition_matrix(self.free_neighbors, self.valid_cells)

        # distance from every free cell to tower with random noise element
        self.dist_tower_range = dist_to_tower_range(self.valid_cells, self.towers)

        # given noisy distance, which cells are most probable during each 11 time-steps
        self.obs_likely_cells = find_obs_likely_cells(self.noisy_distance, self.dist_tower_range, self.valid_cells)

        # get emission matrix for each observation
        self.emis_matrix_list, self.emis_matrix_index_list = emission_matrices(self.obs_likely_cells, self.free_neighbors, self.valid_cells)

        #Flatten the observation emission matrixes into a list of dicts
        self.E_list = flatten_emis(self.emis_matrix_list, self.emis_matrix_index_list)

robot = robot_stats()



