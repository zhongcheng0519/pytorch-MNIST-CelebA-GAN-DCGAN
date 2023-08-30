import os
import matplotlib.pyplot as plt
import itertools
import pickle
import imageio
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.autograd import Variable
os.environ['KMP_DUPLICATE_LIB_OK']='True'


device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


class Generator(nn.Module):
    # initializers
    def __init__(self, input_size=32, n_class = 10):
        super(Generator, self).__init__()
        self.fc1 = nn.Linear(input_size, 256)
        self.fc2 = nn.Linear(self.fc1.out_features, 512)
        self.fc3 = nn.Linear(self.fc2.out_features, 1024)
        self.fc4 = nn.Linear(self.fc3.out_features, n_class)

    # forward method
    def forward(self, input):
        x = F.leaky_relu(self.fc1(input), 0.2)
        x = F.leaky_relu(self.fc2(x), 0.2)
        x = F.leaky_relu(self.fc3(x), 0.2)
        x = F.tanh(self.fc4(x))

        return x


class Discriminator(nn.Module):
    # initializers
    def __init__(self, input_size=784, n_class=10):
        super(Discriminator, self).__init__()
        self.fc1 = nn.Linear(input_size, 1024)
        self.fc2 = nn.Linear(self.fc1.out_features, 512)
        self.fc3 = nn.Linear(self.fc2.out_features, 256)
        self.fc4 = nn.Linear(self.fc3.out_features, n_class)

    # forward method
    def forward(self, input):
        x = F.leaky_relu(self.fc1(input), 0.2)
        x = F.dropout(x, 0.3)
        x = F.leaky_relu(self.fc2(x), 0.2)
        x = F.dropout(x, 0.3)
        x = F.leaky_relu(self.fc3(x), 0.2)
        x = F.dropout(x, 0.3)
        x = F.sigmoid(self.fc4(x))

        return x.flatten()


def show_result(G, num_epoch, show=False, save=False, path='result.png', isFix=False):
    z = torch.randn((5*5, 100)).to(device)
    fixed_z = torch.randn((5 * 5, 100)).to(device)  # fixed noise
    G.eval()
    if isFix:
        test_images = G(fixed_z)
    else:
        test_images = G(z)
    G.train()

    size_figure_grid = 5
    fig, ax = plt.subplots(size_figure_grid, size_figure_grid, figsize=(5, 5))
    for i, j in itertools.product(range(size_figure_grid), range(size_figure_grid)):
        ax[i, j].get_xaxis().set_visible(False)
        ax[i, j].get_yaxis().set_visible(False)

    for k in range(5*5):
        i = k // 5
        j = k % 5
        ax[i, j].cla()
        ax[i, j].imshow(test_images[k, :].cpu().data.view(28, 28).numpy(), cmap='gray')

    label = f'Epoch {num_epoch}'
    fig.text(0.5, 0.04, label, ha='center')
    if save:
        plt.savefig(path)

    if show:
        plt.show()
    else:
        plt.close()


def show_train_hist(hist, show = False, save = False, path = 'Train_hist.png'):
    x = range(len(hist['D_losses']))

    y1 = hist['D_losses']
    y2 = hist['G_losses']

    plt.plot(x, y1, label='D_loss')
    plt.plot(x, y2, label='G_loss')

    plt.xlabel('Epoch')
    plt.ylabel('Loss')

    plt.legend(loc=4)
    plt.grid(True)
    plt.tight_layout()

    if save:
        plt.savefig(path)

    if show:
        plt.show()
    else:
        plt.close()


def main():
    # training parameters
    batch_size = 128
    lr = 0.0002
    train_epoch = 100

    # data_loader
    transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=0.5, std=0.5)
    ])
    train_loader = torch.utils.data.DataLoader(
        datasets.MNIST('data', train=True, download=True, transform=transform),
        batch_size=batch_size, shuffle=True)

    # network
    G = Generator(input_size=100, n_class=28 * 28)
    D = Discriminator(input_size=28 * 28, n_class=1)


    G.to(device)
    D.to(device)

    # Binary Cross Entropy loss
    BCE_loss = nn.BCELoss()

    # Adam optimizer
    G_optimizer = optim.Adam(G.parameters(), lr=lr)
    D_optimizer = optim.Adam(D.parameters(), lr=lr)

    # results save folder
    if not os.path.isdir('MNIST_GAN_results'):
        os.mkdir('MNIST_GAN_results')
    if not os.path.isdir('MNIST_GAN_results/Random_results'):
        os.mkdir('MNIST_GAN_results/Random_results')
    if not os.path.isdir('MNIST_GAN_results/Fixed_results'):
        os.mkdir('MNIST_GAN_results/Fixed_results')


    train_hist = {}
    train_hist['D_losses'] = []
    train_hist['G_losses'] = []
    for epoch in range(train_epoch):
        D_losses = []
        G_losses = []
        for x, _ in train_loader:
            # train discriminator D
            D.zero_grad()

            x = x.view(-1, 28 * 28).to(device)

            mini_batch = x.size()[0]

            y_real = torch.ones(mini_batch).to(device)
            y_fake = torch.zeros(mini_batch).to(device)

            D_result = D(x)
            D_real_loss = BCE_loss(D_result, y_real)
            D_real_score = D_result

            z = torch.randn((mini_batch, 100))
            z = Variable(z.to(device))
            G_result = G(z)

            D_result = D(G_result)
            D_fake_loss = BCE_loss(D_result, y_fake)
            D_fake_score = D_result

            D_train_loss = D_real_loss + D_fake_loss

            D_train_loss.backward()
            D_optimizer.step()

            D_losses.append(D_train_loss.data.item())

            # train generator G
            G.zero_grad()

            z = torch.randn((mini_batch, 100)).to(device)
            y = torch.ones(mini_batch).to(device)

            G_result = G(z)
            D_result = D(G_result)
            G_train_loss = BCE_loss(D_result, y)
            G_train_loss.backward()
            G_optimizer.step()

            G_losses.append(G_train_loss.data.item())

        print('[%d/%d]: loss_d: %.3f, loss_g: %.3f' % (
            (epoch + 1), train_epoch, torch.mean(torch.FloatTensor(D_losses)), torch.mean(torch.FloatTensor(G_losses))))
        p = 'MNIST_GAN_results/Random_results/MNIST_GAN_' + str(epoch + 1) + '.png'
        fixed_p = 'MNIST_GAN_results/Fixed_results/MNIST_GAN_' + str(epoch + 1) + '.png'
        show_result(G, (epoch+1), save=True, path=p, isFix=False)
        show_result(G, (epoch+1), save=True, path=fixed_p, isFix=True)
        train_hist['D_losses'].append(torch.mean(torch.FloatTensor(D_losses)))
        train_hist['G_losses'].append(torch.mean(torch.FloatTensor(G_losses)))


    print("Training finish!... save training results")
    torch.save(G.state_dict(), "MNIST_GAN_results/generator_param.pkl")
    torch.save(D.state_dict(), "MNIST_GAN_results/discriminator_param.pkl")
    with open('MNIST_GAN_results/train_hist.pkl', 'wb') as f:
        pickle.dump(train_hist, f)

    show_train_hist(train_hist, save=True, path='MNIST_GAN_results/MNIST_GAN_train_hist.png')

    images = []
    for e in range(train_epoch):
        img_name = 'MNIST_GAN_results/Fixed_results/MNIST_GAN_' + str(e + 1) + '.png'
        images.append(imageio.v2.imread(img_name))
    imageio.mimsave('MNIST_GAN_results/generation_animation.gif', images, fps=5)


if __name__ == "__main__":
    main()
